const BASE_URL = process.env.JUERI_BASE_URL!
const TOKEN    = process.env.JUERI_TOKEN!

async function fetchPage(endpoint: string, page: number): Promise<{ data: unknown[]; next_page_url: string | null }> {
  const url = `${BASE_URL}/${endpoint}?page=${page}`
  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${TOKEN}`, Accept: 'application/json' },
    next: { revalidate: 300 }, // cache 5 min
  })
  if (!res.ok) throw new Error(`Jueri API error: ${res.status}`)
  return res.json()
}

export async function getAllPages(endpoint: string): Promise<unknown[]> {
  const results: unknown[] = []
  let page = 1
  while (true) {
    const data = await fetchPage(endpoint, page)
    results.push(...data.data)
    if (!data.next_page_url) break
    page++
  }
  return results
}
