export function slugify(value: string, fallback = 'item') {
  const slug = value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 128)

  return slug || fallback
}

export function normalizeOptionalSlug(
  slug: string | undefined,
  name: string,
  fallback = 'item',
) {
  return slugify(slug?.trim() || name, fallback)
}
