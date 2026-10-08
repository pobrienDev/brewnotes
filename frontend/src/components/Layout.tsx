import { Link, Outlet } from 'react-router'

export function Layout() {
  return (
    <div className="min-h-screen flex flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <nav className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <Link to="/" className="text-lg font-semibold text-amber-700">
            BrewNotes
          </Link>
        </nav>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>
      <footer className="border-t border-stone-200 py-4 text-center text-sm text-stone-500">
        <Link to="/privacy" className="hover:underline">
          Privacy
        </Link>
      </footer>
    </div>
  )
}
