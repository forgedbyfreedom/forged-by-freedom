// backend/http-functions.js
import { ok, serverError } from 'wix-http-functions';

// Example API endpoint: https://www.forgedbyfreedom.com/_functions/getData
export async function get_getData(request) {
  try {
    const response = await fetch(
      'https://raw.githubusercontent.com/forgedbyfreedom/fbf-data/main/combined.json'
    );
    if (!response.ok) throw new Error('Failed to fetch data from GitHub');
    const data = await response.json();

    return ok({
      headers: { 'Content-Type': 'application/json' },
      body: data,
    });
  } catch (err) {
    return serverError({
      headers: { 'Content-Type': 'application/json' },
      body: { error: err.message },
    });
  }
}
