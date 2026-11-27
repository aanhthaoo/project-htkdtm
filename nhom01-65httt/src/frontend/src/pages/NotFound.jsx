import { Link } from "react-router-dom";

export default function NotFound() {
  return (
    <div className="p-8 text-center">
      <h1 className="text-2xl font-semibold">Không tìm thấy trang</h1>
      <Link to="/" className="mt-4 inline-block text-brand-600 hover:underline">
        Về trang tổng quan
      </Link>
    </div>
  );
}
