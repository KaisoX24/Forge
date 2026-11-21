export function matchesQuery(course: { title: string; framework: string }, query: string) {
  const q = query.trim().toLowerCase();
  return !q || course.title.toLowerCase().includes(q) || course.framework.toLowerCase().includes(q);
}