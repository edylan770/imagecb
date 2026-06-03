import { BrowserRouter, Route, Routes } from "react-router-dom";
import App from "./App";
import AdminApp from "./admin/AdminApp";

export default function Root() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/admin/*" element={<AdminApp />} />
      </Routes>
    </BrowserRouter>
  );
}
