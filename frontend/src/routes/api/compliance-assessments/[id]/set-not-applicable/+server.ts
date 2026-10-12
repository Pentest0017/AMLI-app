import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ fetch, params, request }) => {
	const backendUrl = `${BASE_API_URL}/compliance-assessments/${params.id}/set-not-applicable/`;
	try {
		const headers: Record<string, string> = { 'Content-Type': 'application/json' };
		const cookie = request.headers.get('cookie') || '';
		if (cookie) headers['cookie'] = cookie;

		let auth = request.headers.get('authorization');
		if (!auth && cookie) {
			const match = cookie.match(/(?:^|;\s*)token=([^;]+)/);
			if (match) auth = `Token ${decodeURIComponent(match[1])}`;
		}
		if (auth) headers['authorization'] = auth;

		const body = await request.text();
		const res = await fetch(backendUrl, {
			method: 'POST',
			headers,
			body
		});
		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};
