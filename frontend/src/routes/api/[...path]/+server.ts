import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

function getForwardHeaders(request: Request): Record<string, string> {
	const headers: Record<string, string> = {};
	
	for (const [key, value] of request.headers.entries()) {
		const lowerKey = key.toLowerCase();
		if (
			lowerKey === 'content-type' ||
			lowerKey === 'cookie' ||
			lowerKey === 'authorization' ||
			lowerKey === 'x-csrftoken' ||
			lowerKey === 'referer' ||
			lowerKey === 'origin'
		) {
			headers[lowerKey] = value;
		}
	}

	const cookie = headers['cookie'] || '';
	if (!headers['authorization'] && cookie) {
		const match = cookie.match(/(?:^|;\s*)token=([^;]+)/);
		if (match) {
			headers['authorization'] = `Token ${decodeURIComponent(match[1])}`;
		}
	}

	return headers;
}

export const GET: RequestHandler = async ({ fetch, params, url, request }) => {
	const backendUrl = `${BASE_API_URL}/${params.path}${url.search}`;
	try {
		const res = await fetch(backendUrl, {
			headers: getForwardHeaders(request)
		});
		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};

export const POST: RequestHandler = async ({ fetch, params, url, request }) => {
	const backendUrl = `${BASE_API_URL}/${params.path}${url.search}`;
	try {
		const headers = getForwardHeaders(request);
		const body = await request.arrayBuffer();

		const res = await fetch(backendUrl, {
			method: 'POST',
			headers,
			body
		});

		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};

export const PATCH: RequestHandler = async ({ fetch, params, url, request }) => {
	const backendUrl = `${BASE_API_URL}/${params.path}${url.search}`;
	try {
		const headers = getForwardHeaders(request);
		const body = await request.arrayBuffer();

		const res = await fetch(backendUrl, {
			method: 'PATCH',
			headers,
			body
		});

		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};

export const PUT: RequestHandler = async ({ fetch, params, url, request }) => {
	const backendUrl = `${BASE_API_URL}/${params.path}${url.search}`;
	try {
		const headers = getForwardHeaders(request);
		const body = await request.arrayBuffer();

		const res = await fetch(backendUrl, {
			method: 'PUT',
			headers,
			body
		});

		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};

export const DELETE: RequestHandler = async ({ fetch, params, url, request }) => {
	const backendUrl = `${BASE_API_URL}/${params.path}${url.search}`;
	try {
		const res = await fetch(backendUrl, {
			method: 'DELETE',
			headers: getForwardHeaders(request)
		});
		const data = await res.text();
		return new Response(data, {
			status: res.status,
			headers: { 'Content-Type': res.headers.get('Content-Type') || 'application/json' }
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), { status: 500 });
	}
};
