const BASE_URL = process.env.JUERI_BASE_URL!
const TOKEN    = process.env.JUERI_TOKEN!

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function fetchPage(endpoint: string, page: number): Promise<{ data: unknown[]; next_page_url: string | null }> {
  const url = `${BASE_URL}/${endpoint}?page=${page}`

  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/json' },
      cache: 'no-store',
    })

    if (res.status === 429) {
      const wait = 8000 * (attempt + 1) // 8s, 16s, 24s, 32s
      await sleep(wait)
      continue
    }

    if (!res.ok) throw new Error(`Jueri API error: ${res.status}`)
    return res.json()
  }

  throw new Error('Jueri API error: 429 — rate limit persistente')
}

export async function getAllPages(endpoint: string): Promise<unknown[]> {
  const results: unknown[] = []
  let page = 1
  while (true) {
    const data = await fetchPage(endpoint, page)
    results.push(...data.data)
    if (!data.next_page_url) break
    page++
    await sleep(300) // pausa entre páginas para não estressar a API
  }
  return results
}
