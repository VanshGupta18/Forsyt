import heroGlobeVideo from '../assets/hero-globe-rays.mp4'

const FADE_MASK =
  'radial-gradient(circle at 50% 54%, black 0%, black 34%, transparent 56%)'

export default function HeroGlobeVideo({ className }: { className?: string }) {
  return (
    <div className={`${className ?? 'h-[640px] w-[640px]'} relative overflow-hidden rounded-full`}>
      <video
        className="h-full w-full object-cover"
        style={{
          maskImage: FADE_MASK,
          WebkitMaskImage: FADE_MASK,
        }}
        autoPlay
        loop
        muted
        playsInline
        src={heroGlobeVideo}
      />
    </div>
  )
}
