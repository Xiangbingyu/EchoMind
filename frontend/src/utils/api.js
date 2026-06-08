export const API_BASE_URL = 'http://localhost:8000';

export async function fetchJson(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

export function createWsUrl(path) {
  return `${API_BASE_URL.replace('http', 'ws')}${path}`;
}
