import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const res = await fetch(`${BASE_API_URL}/users/`);
		if (res.ok) {
			const data = await res.json();
			const users = Array.isArray(data) ? data : (data.results ?? []);
			return { users };
		}
	} catch (e) {
		console.error('Failed to fetch users for company hierarchy:', e);
	}
	return { users: [] };
};
