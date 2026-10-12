import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad } from './$types';

export const load = (async ({ fetch, params }) => {
	const URLModel = 'frameworks';
	const endpoint = `${BASE_API_URL}/${URLModel}/${params.id}/`;
	const treeEndpoint = `${BASE_API_URL}/${URLModel}/${params.id}/tree/`;

	let framework: any = {};
	let tree: any = {};

	try {
		const [fwRes, treeRes] = await Promise.all([
			fetch(endpoint),
			fetch(treeEndpoint)
		]);

		if (fwRes.ok) {
			framework = await fwRes.json();
		}
		if (treeRes.ok) {
			tree = await treeRes.json();
		}
	} catch (e) {
		console.error('Error loading framework detail server-side:', e);
	}

	// Fallback if framework object is invalid/empty or returned error payload
	if (!framework || !framework.id || framework.detail) {
		try {
			const fallbackFwRes = await fetch(`/api/frameworks/${params.id}/`);
			if (fallbackFwRes.ok) {
				framework = await fallbackFwRes.json();
			}
		} catch (err) {
			console.error('Fallback fetch for framework failed:', err);
		}
	}

	return {
		URLModel,
		framework: framework || {},
		tree: tree && !tree.detail ? tree : {},
		title: framework?.name || 'Library Detail'
	};
}) satisfies PageServerLoad;
