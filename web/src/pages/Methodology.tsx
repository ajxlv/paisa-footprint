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
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Wide code blocks and tables scroll; make them keyboard-reachable (axe: scrollable-region-focusable).
          pre: ({ node: _node, ...props }) => <pre tabIndex={0} {...props} />,
          table: ({ node: _node, ...props }) => (
            <div className="overflow-x-auto" tabIndex={0} role="region" aria-label="Table, scrollable">
              <table {...props} />
            </div>
          ),
        }}
      >
        {data?.markdown ?? ''}
      </ReactMarkdown>
    </article>
  );
}
