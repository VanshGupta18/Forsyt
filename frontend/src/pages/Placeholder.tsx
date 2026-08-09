export default function Placeholder({ title }: { title: string }) {
  return (
    <section className="px-margin-page max-w-container-max mx-auto py-32 min-h-[60vh] flex flex-col items-center justify-center text-center gap-4">
      <span className="material-symbols-outlined text-primary text-5xl">construction</span>
      <h1 className="font-headline-lg text-on-surface">{title}</h1>
      <p className="font-body-md text-on-surface-variant max-w-md">
        This module's screen hasn't been generated in Stitch yet. Once you export its code from the
        Stitch project, it can be pulled in here the same way the landing page was.
      </p>
    </section>
  )
}
