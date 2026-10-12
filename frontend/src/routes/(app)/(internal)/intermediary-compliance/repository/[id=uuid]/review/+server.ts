import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async (event) => {
	let body = {};
	try {
		body = await event.request.json();
	} catch (e) {}

	const endpoint = `${BASE_API_URL}/intermediary-compliance/partner-reports/${event.params.id}/review/`;

	const res = await event.fetch(endpoint, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});

	if (!res.ok) {
		let errText = 'Failed to submit review';
		try {
			const errData = await res.json();
			errText = errData.error || errText;
		} catch (e) {}
		return new Response(JSON.stringify({ error: errText }), {
			status: res.status,
			headers: { 'Content-Type': 'application/json' }
		});
	}

	return new Response(JSON.stringify(await res.json()), {
		status: 200,
		headers: { 'Content-Type': 'application/json' }
	});
};
