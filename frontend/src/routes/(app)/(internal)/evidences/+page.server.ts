import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const res = await fetch(`${BASE_API_URL}/evidence-repository/?review_status=APPROVED`);
		let items: any[] = [];
		if (res.ok) {
			const data = await res.json();
			items = data.results || data || [];
		}
		return { items };
	} catch (err) {
		console.error('Failed to load approved evidence library server data:', err);
		return { items: [] };
	}
};
