"""Bedrock Titan Multimodal Embeddings wrapper.



Uses ``amazon.titan-embed-image-v1`` via ``bedrock-runtime.invoke_model``

for both image and text inputs in a shared embedding space. Vectors are

L2-normalized so cosine similarity equals inner product in Chroma.

"""



from __future__ import annotations



import base64

import io

import json

from typing import Iterable, List, Optional



import numpy as np

from PIL import Image



from imagecb.config import SETTINGS

from imagecb.models.bedrock_client import get_bedrock_runtime



_MAX_IMAGE_SIDE = 2048





def _prepare_image(image: Image.Image) -> str:

    img = image.convert("RGB")

    w, h = img.size

    if max(w, h) > _MAX_IMAGE_SIDE:

        scale = _MAX_IMAGE_SIDE / max(w, h)

        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()

    img.save(buf, format="PNG")

    return base64.b64encode(buf.getvalue()).decode("ascii")





def _normalize(vec: np.ndarray) -> np.ndarray:

    norm = np.linalg.norm(vec)

    if norm > 0:

        vec = vec / norm

    return vec.astype(np.float32)





def _is_cohere_embed(model_id: str) -> bool:
    return "cohere" in model_id and "embed" in model_id


class BedrockEmbedder:

    def __init__(self, model_id: Optional[str] = None, dim: Optional[int] = None) -> None:

        self.model_id = model_id or SETTINGS.embedding_model

        self._dim = dim or SETTINGS.embedding_dim

        self._cohere = _is_cohere_embed(self.model_id)



    @property

    def dim(self) -> int:

        return self._dim



    def _invoke_cohere(
        self,
        *,
        input_text: Optional[str] = None,
        input_image_b64: Optional[str] = None,
        input_type: str,
    ) -> np.ndarray:
        body: dict = {
            "input_type": input_type,
            "embedding_types": ["float"],
            "output_dimension": self._dim,
        }
        if input_text is not None:
            body["texts"] = [input_text]
        if input_image_b64 is not None:
            body["images"] = [f"data:image/png;base64,{input_image_b64}"]

        response = get_bedrock_runtime().invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            accept="*/*",
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        embedding = np.array(result["embeddings"]["float"][0], dtype=np.float32)
        return _normalize(embedding)

    def _invoke_titan(
        self, *, input_text: Optional[str] = None, input_image_b64: Optional[str] = None
    ) -> np.ndarray:
        body: dict = {"embeddingConfig": {"outputEmbeddingLength": self._dim}}
        if input_text is not None:
            body["inputText"] = input_text
        if input_image_b64 is not None:
            body["inputImage"] = input_image_b64

        response = get_bedrock_runtime().invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
            accept="application/json",
            contentType="application/json",
        )
        result = json.loads(response["body"].read())
        embedding = np.array(result["embedding"], dtype=np.float32)
        return _normalize(embedding)

    def _invoke(self, *, input_text: Optional[str] = None, input_image_b64: Optional[str] = None) -> np.ndarray:
        if self._cohere:
            input_type = "search_query" if input_text is not None else "search_document"
            return self._invoke_cohere(
                input_text=input_text,
                input_image_b64=input_image_b64,
                input_type=input_type,
            )
        return self._invoke_titan(input_text=input_text, input_image_b64=input_image_b64)



    def embed_image(self, image: Image.Image) -> np.ndarray:

        return self.embed_images([image])[0]

    def embed_image_with_context(
        self, image: Image.Image, context: Optional[str] = None
    ) -> np.ndarray:
        """Embed image; when context is set, include slide/PDF text (Titan only)."""
        ctx = (context or "").strip()
        b64 = _prepare_image(image)
        if ctx and not self._cohere:
            return self._invoke(input_text=ctx, input_image_b64=b64)
        return self._invoke(input_image_b64=b64)

    def embed_images(self, images: Iterable[Image.Image]) -> np.ndarray:

        return np.stack([self._invoke(input_image_b64=_prepare_image(img)) for img in images])



    def embed_text(self, texts: List[str]) -> np.ndarray:

        if not texts:

            return np.zeros((0, self._dim), dtype=np.float32)

        return np.stack([self._invoke(input_text=t) for t in texts])





_embedder: Optional[BedrockEmbedder] = None





def get_embedder() -> BedrockEmbedder:

    global _embedder

    if _embedder is None:

        _embedder = BedrockEmbedder()

    return _embedder


