"""Typer-based command-line entrypoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer

from imagecb.config import SETTINGS

app = typer.Typer(add_completion=False, help="Conversational multimodal image retrieval.")


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def ingest(
    path: Path = typer.Argument(..., exists=True, readable=True, help="File or directory to ingest."),
    skip_caption: bool = typer.Option(
        False,
        "--skip-caption",
        help="Skip the VLM caption step (useful for an offline dry-run; quality of search will drop).",
    ),
    skip_ocr: bool = typer.Option(
        False,
        "--skip-ocr",
        help="Skip Tesseract OCR during ingest (faster; OCR fields will be empty).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-process images already in the index (re-cache PNGs, re-caption, refresh vectors).",
    ),
    workers: int = typer.Option(
        SETTINGS.ingest_workers,
        "--workers",
        min=1,
        help="Parallel ingest workers (Bedrock calls are I/O-bound; try 4-8).",
    ),
    max_image_side: int = typer.Option(
        SETTINGS.ingest_max_image_side,
        "--max-image-side",
        min=256,
        help="Longest edge sent to the VLM for captioning (smaller is faster).",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Walk PATH and ingest every supported image into the index."""
    _configure_logging(verbose)
    from imagecb.ingest import ingest_root

    stats = ingest_root(
        path,
        skip_caption=skip_caption,
        skip_ocr=skip_ocr,
        force=force,
        workers=workers,
        max_image_side=max_image_side,
    )
    elapsed = stats.get("elapsed_sec", 0)
    rate = ""
    processed = stats["images_added"] + stats["images_updated"]
    if elapsed > 0 and processed > 0:
        rate = f" ({processed / elapsed:.2f} images/s)"
    typer.echo(
        f"Done in {elapsed}s{rate}. workers={stats.get('workers', workers)} "
        f"files={stats['files']} images_seen={stats['images_seen']} "
        f"added={stats['images_added']} updated={stats['images_updated']} "
        f"duplicates={stats['skipped_duplicates']} errors={stats['errors']}"
    )


@app.command(name="serve-web")
def serve_web(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(8080, help="Bind port."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Launch the FastAPI web UI (no npm required)."""
    _configure_logging(verbose)
    from imagecb.api.server import launch

    typer.echo(f"Imagecb web UI at http://{host}:{port}")
    launch(host=host, port=port)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host."),
    port: int = typer.Option(7860, help="Bind port."),
    share: bool = typer.Option(False, help="Create a public Gradio share link."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Launch the legacy Gradio chat UI."""
    _configure_logging(verbose)
    from imagecb.app import launch

    launch(host=host, port=port, share=share)


@app.command()
def status() -> None:
    """Print a quick summary of the current index."""
    from pathlib import Path

    from imagecb.storage import metadata_db, vector_store

    SETTINGS.ensure_dirs()
    records = metadata_db.get_all_records()
    n_vec = 0
    try:
        n_vec = vector_store.count()
    except Exception:  # noqa: BLE001
        pass
    missing_cache = sum(
        1 for r in records if not Path(r.image_path).expanduser().is_file()
    )
    caption_failed = sum(
        1 for r in records if (r.caption_short or "").strip() == "[caption failed]"
    )
    typer.echo(
        f"SQLite records: {len(records)} | Chroma vectors: {n_vec} | "
        f"Chroma dir: {SETTINGS.chroma_dir} | SQLite: {SETTINGS.sqlite_path}"
    )
    typer.echo(
        f"Missing cached PNGs: {missing_cache} | Captions failed at ingest: {caption_failed}"
    )
    if missing_cache or caption_failed:
        typer.echo(
            "Re-ingest your original image folder with working Bedrock auth, e.g.\n"
            '  python -m imagecb.cli ingest "C:\\path\\to\\images" --force'
        )


@app.command(name="validate-reranker")
def validate_reranker_cmd(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    """Smoke-test Bedrock reranker access for the configured region and model."""
    _configure_logging(verbose)
    from imagecb.models.reranker import get_reranker

    region = SETTINGS.aws_region
    model = SETTINGS.reranker_model
    typer.echo(f"Region: {region}")
    typer.echo(f"Reranker model: {model}")
    try:
        scores = get_reranker().score(
            "cyber security",
            ["A network operations center with security dashboards.", "A beach at sunset."],
        )
        typer.echo(f"OK. Sample scores: {scores}")
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"FAILED: {exc}", fg=typer.colors.RED, err=True)
        msg = str(exc).lower()
        name = type(exc).__name__
        if name == "AccessDeniedException" or "authentication failed" in msg:
            typer.echo(
                "Bedrock rejected the API key for this region. Short-lived "
                "AWS_BEARER_TOKEN_BEDROCK keys are tied to the region where you "
                "created them. After changing AWS_REGION in .env, generate a NEW "
                "key in the Bedrock console for that same region (e.g. us-east-1), "
                "or use standard IAM credentials (aws configure).",
                err=True,
            )
            typer.echo(
                "In the Bedrock console (same region as AWS_REGION), open Model "
                "access and enable cohere.rerank-v3-5:0, your embedding model, "
                "and your Claude model.",
                err=True,
            )
        elif "model identifier is invalid" in msg:
            typer.echo(
                "Cohere Rerank 3.5 (cohere.rerank-v3-5:0) is supported in us-east-1, "
                "us-west-2, ca-central-1, eu-central-1, and ap-northeast-1 (not us-east-2). "
                "Set AWS_REGION to a supported region in .env.",
                err=True,
            )
        else:
            typer.echo(
                "Check AWS_REGION, RERANKER_MODEL, and Bedrock model access in the console.",
                err=True,
            )
        raise typer.Exit(1) from exc


@app.command(name="repair-captions")
def repair_captions_cmd(
    workers: int = typer.Option(
        SETTINGS.ingest_workers,
        "--workers",
        min=1,
        help="Parallel VLM workers.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-run VLM captioning for images that failed during ingest."""
    _configure_logging(verbose)
    from imagecb.repair import repair_failed_captions

    stats = repair_failed_captions(workers=workers)
    typer.echo(
        f"Done in {stats.get('elapsed_sec', 0)}s. "
        f"attempted={stats['attempted']} repaired={stats['repaired']} errors={stats['errors']}"
    )


@app.command(name="reindex-embeddings")
def reindex_embeddings_cmd(
    workers: int = typer.Option(
        SETTINGS.ingest_workers,
        "--workers",
        min=1,
        help="Parallel embedding workers.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Re-embed all cached images (e.g. after enabling slide/PDF context vectors)."""
    _configure_logging(verbose)
    from imagecb.repair import reindex_embeddings

    stats = reindex_embeddings(workers=workers)
    typer.echo(
        f"Done in {stats.get('elapsed_sec', 0)}s. "
        f"records={stats['records']} reindexed={stats['reindexed']} errors={stats['errors']}"
    )


@app.command(name="parse-query")
def parse_query_cmd(text: str = typer.Argument(..., help="A natural-language query to parse.")) -> None:
    """Debug helper: print the parsed QuerySpec for TEXT."""
    from imagecb.retrieval.query_parser import parse_query

    spec = parse_query(text)
    typer.echo(
        f"semantic_query : {spec.semantic_query}\n"
        f"must_have      : {spec.must_have_keywords}\n"
        f"must_avoid     : {spec.must_avoid_keywords}\n"
        f"file_types     : {spec.source_filters.file_types}\n"
        f"filename_like  : {spec.source_filters.filename_contains}\n"
        f"authors        : {spec.source_filters.authors}\n"
        f"after          : {spec.time_filter.after}\n"
        f"before         : {spec.time_filter.before}\n"
        f"top_k          : {spec.top_k}\n"
        f"is_refinement  : {spec.is_refinement}"
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
