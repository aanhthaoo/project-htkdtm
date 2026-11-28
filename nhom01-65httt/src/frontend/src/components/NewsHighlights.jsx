import Alert from "./Alert.jsx";
import Button from "./Button.jsx";
import Card from "./Card.jsx";
import Spinner from "./Spinner.jsx";
import useApi from "./useApi.js";

export default function NewsHighlights() {
  const { data, loading, error, reload } = useApi("/api/news/highlights");
  return (
    <Card title="Tin nổi bật">
      {loading && <Spinner />}
      {error && (
        <Alert kind="error">
          Không tải được tin nổi bật. <Button variant="secondary" onClick={reload}>Thử lại</Button>
        </Alert>
      )}
      {!loading && data && (data.items.length === 0 ? (
        <p className="text-sm text-slate-600">Chưa có tin nổi bật.</p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((article) => (
            <li key={article.url}>
              <a className="font-medium text-brand-700 hover:underline" href={article.url} target="_blank" rel="noreferrer">
                {article.title}
              </a>
              <p className="text-sm text-slate-500">{article.source} · {article.session_date}</p>
            </li>
          ))}
        </ul>
      ))}
    </Card>
  );
}
