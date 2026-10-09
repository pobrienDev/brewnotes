import { Link, NavLink, Outlet } from 'react-router'

import { useMe } from '../hooks/useMe'
import { SignOutButton } from './SignOutButton'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-2 py-1 text-sm ${isActive ? 'bg-amber-100 text-amber-900' : 'text-stone-700 hover:bg-stone-100'}`

export function Layout() {
  const me = useMe()
  return (
    <div className="flex min-h-screen flex-col bg-stone-50 text-stone-900">
      <header className="border-b border-stone-200 bg-white">
        <nav aria-label="Main" className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-4 text-lg font-semibold text-amber-700">
            BrewNotes
          </Link>
          <NavLink to="/recipes/new" className={navClass}>
            Calculator
          </NavLink>
          <NavLink to="/styles" className={navClass}>
            Styles
          </NavLink>
          {me.data && (
            <>
              <NavLink to="/recipes" className={navClass} end>
                My recipes
              </NavLink>
              <NavLink to="/batches" className={navClass}>
                Batches
              </NavLink>
              <NavLink to="/beers" className={navClass}>
                Beers
              </NavLink>
              <NavLink to="/tastings" className={navClass}>
                Tastings
              </NavLink>
              <NavLink to="/ingredients" className={navClass}>
                My ingredients
              </NavLink>
            </>
          )}
          <span className="flex-1" />
          {me.data ? (
            <div className="flex items-center gap-3">
              <NavLink to="/account" className={navClass}>
                <span className="flex items-center gap-2">
                  {me.data.avatar_url && (
                    <img src={me.data.avatar_url} alt="" className="h-6 w-6 rounded-full" />
                  )}
                  {me.data.display_name}
                </span>
              </NavLink>
              <SignOutButton />
            </div>
          ) : (
            <NavLink to="/sign-in" className={navClass}>
              Sign in
            </NavLink>
          )}
        </nav>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
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
