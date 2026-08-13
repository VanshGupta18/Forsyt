import Hero from '../components/Hero'
import HeroMarquee from '../components/HeroMarquee'
import EdgeSection from '../components/EdgeSection'
import SectionDivider from '../components/SectionDivider'
import CapabilityHub from '../components/CapabilityHub'
import Modules from '../components/Modules'
import MissionSection from '../components/MissionSection'
import GetStartedSection from '../components/GetStartedSection'
import PageRail from '../components/PageRail'

export default function Home() {
  return (
    <>
      <PageRail />
      <Hero />
      <HeroMarquee />
      <EdgeSection />
      <SectionDivider />
      <CapabilityHub />
      <SectionDivider />
      <Modules />
      <SectionDivider />
      <MissionSection />
      <SectionDivider />
      <GetStartedSection />
    </>
  )
}
