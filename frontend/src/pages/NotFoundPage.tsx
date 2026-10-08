import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <section className="space-y-2">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p>
        <Link to="/" className="text-amber-700 hover:underline">
          Back to the start
        </Link>
      </p>
    </section>
  )
}
