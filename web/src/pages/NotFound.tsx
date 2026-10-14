import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <Link to="/" className="mt-4 inline-block underline">Back to home</Link>
    </div>
  );
}
