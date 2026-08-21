// Home page's top section: lays out HeroVerdictBlock (text + stats) next to
// HeroGlobe (the spinning globe visual).
import HeroGlobe from './HeroGlobe'
import HeroVerdictBlock from './HeroVerdictBlock'
import type { HomeLiveData } from '../hooks/useHomeLiveData'

type Props = {
  live: HomeLiveData
}

export default function Hero({ live }: Props) {
  return (
    <section id="section-01">
      <div className="home-hero-intro max-w-container-max mx-auto px-margin-page">
        <div className="home-hero-cluster flex flex-col lg:grid lg:grid-cols-[minmax(0,1fr)_min(440px,38%)] lg:gap-4 xl:gap-6 lg:items-center mx-auto w-full">
          <HeroVerdictBlock live={live} />

          <div className="order-1 lg:order-2 shrink-0 flex justify-center lg:justify-end home-hero-globe">
            <HeroGlobe
              className="w-[min(100%,320px)] sm:w-[360px] lg:w-full xl:max-w-[440px] aspect-square"
              corridors={live.corridors}
              metadata={live.corridorMetadata}
            />
          </div>
        </div>
      </div>
    </section>
  )
}
