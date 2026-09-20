// "Related coverage" — articles that are semantically close to this one, found
// by k-NN over the embeddings the NLP pipeline already computes (see
// news_dataset/search/opensearch_client.py). This is the one thing the keyword
// path can't do: it matches tags and substrings, not meaning, so a story about
// the same event in different words is invisible to it.
//
// Renders nothing at all when the backend has no OpenSearch configured (the
// normal case outside the compose stack) — an absent optional feature should
// not leave an empty box on the page.
import { useQuery } from '@tanstack/react-query'
import { fetchRelatedNews } from '../lib/api'

export default function RelatedCoveragePanel({ articleId }: { articleId?: number | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['related-news', articleId],
    queryFn: () => fetchRelatedNews(articleId as number),
    enabled: Boolean(articleId),
    retry: false,
    staleTime: 15 * 60 * 1000,
  })

  if (!articleId || isLoading) return null
  if (!data?.enabled || !data.related.length) return null

  return (
    <section className="corridor-panel p-3">
      <div className="flex items-center justify-between mb-2">
        <h2 className="corridor-kicker text-white normal-case tracking-wide text-sm font-bold">
          Related coverage
        </h2>
        <span className="text-[9px] uppercase tracking-wide text-corridor-muted/60">Semantic match</span>
      </div>
      <ul className="space-y-1.5">
        {data.related.map((r) => (
          <li key={r.article_id} className="text-xs leading-snug">
            <a
              href={r.link ?? '#'}
              target="_blank"
              rel="noreferrer"
              className="text-corridor-muted hover:text-white underline-offset-2 hover:underline"
            >
              {r.title ?? 'Untitled'}
            </a>
          </li>
        ))}
      </ul>
    </section>
  )
}
