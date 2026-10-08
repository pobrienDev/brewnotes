import { Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { RequireAuth } from './components/RequireAuth'
import { AccountPage } from './pages/AccountPage'
import { HomePage } from './pages/HomePage'
import { IngredientsPage } from './pages/IngredientsPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PrivacyPage } from './pages/PrivacyPage'
import { RecipeEditorPage } from './pages/RecipeEditorPage'
import { RecipesPage } from './pages/RecipesPage'
import { SignInPage } from './pages/SignInPage'
import { StyleComparePage } from './pages/StyleComparePage'
import { StyleDetailPage } from './pages/StyleDetailPage'
import { StylesPage } from './pages/StylesPage'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="sign-in" element={<SignInPage />} />
        <Route path="privacy" element={<PrivacyPage />} />
        <Route path="styles" element={<StylesPage />} />
        <Route path="styles/compare" element={<StyleComparePage />} />
        <Route path="styles/:slug" element={<StyleDetailPage />} />
        <Route path="recipes/new" element={<RecipeEditorPage />} />
        <Route path="recipes" element={<RequireAuth><RecipesPage /></RequireAuth>} />
        <Route path="recipes/:id" element={<RequireAuth><RecipeEditorPage /></RequireAuth>} />
        <Route path="ingredients" element={<RequireAuth><IngredientsPage /></RequireAuth>} />
        <Route path="account" element={<RequireAuth><AccountPage /></RequireAuth>} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
