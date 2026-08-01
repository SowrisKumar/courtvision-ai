import { useState } from 'react'
import { api, type AskResult } from '../lib/api'
import { Card, ErrorNote } from '../components/ui'

const EXAMPLES = [
  'Which team improved its defense the most between 2024-25 and 2025-26?',
  'Compare Luka Doncic and Nikola Jokic this season',
  'Who are the most efficient high-usage scorers in 2025-26?',
  'Which teams win the most on the road?',
]

export default function Ask() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AskResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit(q: string) {
    const trimmed = q.trim()
    if (trimmed.length < 3 || loading) return
    setQuestion(trimmed)
    setLoading(true)
    setError('')
    setResult(null)
    try {
      setResult(await api.ask(trimmed))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Ask CourtVision</h1>
      <p className="max-w-2xl text-sm text-[var(--text-secondary)]">
        Ask any question about the last four NBA seasons. The assistant writes SQL
        against the warehouse, reads the results, and answers with only the numbers
        it found. Every query it ran is shown below the answer.
      </p>

      <form
        className="flex max-w-2xl gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          submit(question)
        }}
      >
        <input
          className="card w-full px-3 py-2 text-sm"
          placeholder="e.g. Why are the Thunder so good?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          aria-label="Question"
        />
        <button
          type="submit"
          disabled={loading || question.trim().length < 3}
          className="card shrink-0 cursor-pointer bg-[var(--series-1)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>

      {!result && !loading && (
        <div className="flex max-w-2xl flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="card cursor-pointer px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              onClick={() => submit(ex)}
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && <ErrorNote message={error} />}
      {loading && (
        <p className="p-4 text-sm text-[var(--text-muted)]">
          Querying the warehouse, this can take a few seconds…
        </p>
      )}

      {result && (
        <>
          <Card title="Answer">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
            <p className="mt-3 text-xs text-[var(--text-muted)]">
              {result.provider} · {result.model} · {result.steps.length} quer
              {result.steps.length === 1 ? 'y' : 'ies'} executed
            </p>
          </Card>

          {result.steps.length > 0 && (
            <Card title="How this answer was produced">
              <div className="space-y-3">
                {result.steps.map((step, i) => (
                  <details key={i} className="rounded-lg border border-[var(--border)] p-3">
                    <summary className="cursor-pointer text-xs font-medium text-[var(--text-secondary)]">
                      Query {i + 1} ({step.total_rows} row{step.total_rows === 1 ? '' : 's'})
                    </summary>
                    <pre className="tabular mt-2 overflow-x-auto rounded bg-[var(--page)] p-2 text-xs whitespace-pre-wrap">
                      {step.sql}
                    </pre>
                    {step.rows.length > 0 && (
                      <pre className="tabular mt-2 max-h-48 overflow-auto rounded bg-[var(--page)] p-2 text-xs">
                        {JSON.stringify(step.rows.slice(0, 10), null, 2)}
                      </pre>
                    )}
                  </details>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
