import Hero from '../components/Hero'
import Modules from '../components/Modules'
import { useHomeLiveData } from '../hooks/useHomeLiveData'

export default function Home() {
  const live = useHomeLiveData()

  return (
    <div className="home-page">
      <Hero live={live} />
      <Modules />
    </div>
  )
}
