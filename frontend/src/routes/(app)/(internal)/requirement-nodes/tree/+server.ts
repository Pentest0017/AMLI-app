import { BASE_API_URL } from '$lib/utils/constants';
import { error, type NumericRange, type RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ fetch, url }) => {
	const query = url.searchParams.toString();
	const endpoint = `${BASE_API_URL}/requirement-nodes/tree/${query ? '?' + query : ''}`;
	const res = await fetch(endpoint);
	if (!res.ok) {
		error(res.status as NumericRange<400, 599>, await res.json());
	}
	const data = await res.json();

	return new Response(JSON.stringify(data), {
		status: 200,
		headers: {
			'Content-Type': 'application/json'
		}
	});
};
