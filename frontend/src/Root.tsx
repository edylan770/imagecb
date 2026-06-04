import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import AdminApp from "./admin/AdminApp";
import DeckSuggestPage from "./pages/DeckSuggestPage";

export default function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/deck" element={<DeckSuggestPage />} />
        <Route path="/admin/*" element={<AdminApp />} />
      </Routes>
    </BrowserRouter>
  );
}
