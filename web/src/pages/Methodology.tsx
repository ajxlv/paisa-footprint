import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { ErrorBox, Loading } from '../components/ui';

export function Methodology() {
  const { data, error, loading } = useApi(api.methodology);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  return (
    <article className="prose-pf max-w-3xl">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{data?.markdown ?? ''}</ReactMarkdown>
    </article>
  );
}
