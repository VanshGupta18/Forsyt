// Route: "/" (the Home page). Shows a hero "today's verdict" banner (news
// risk, market move, top corridor) next to a spinning globe, followed by a
// grid of links into the other modules. See lib/modules.ts for the module list.
import Hero from '../components/Hero'
import Modules from '../components/Modules'
import GprPanelsRow from '../components/GprPanels'
import { useHomeLiveData } from '../hooks/useHomeLiveData'

export default function Home() {
  const live = useHomeLiveData()

  return (
    <div className="home-page">
      <Hero live={live} />
      <div className="px-margin-page max-w-container-max mx-auto w-full pt-10 pb-2">
        <GprPanelsRow panels={live.panels} />
      </div>
      <Modules />
    </div>
  )
}
