import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ fetch, params, request }) => {
	const backendUrl = `${BASE_API_URL}/compliance-assessments/${params.id}/controls-detail/`;
	try {
		const headers: Record<string, string> = { 'Accept': 'application/json' };
		const cookie = request.headers.get('cookie') || '';
		if (cookie) headers['cookie'] = cookie;

		let auth = request.headers.get('authorization');
		if (!auth && cookie) {
			const match = cookie.match(/(?:^|;\s*)token=([^;]+)/);
			if (match) auth = `Token ${decodeURIComponent(match[1])}`;
		}
		if (auth) headers['authorization'] = auth;

		const res = await fetch(backendUrl, { headers });
		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message, controls: [] }), { status: 500 });
	}
};
