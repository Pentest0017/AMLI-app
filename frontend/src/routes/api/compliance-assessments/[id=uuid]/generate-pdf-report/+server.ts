import { BASE_API_URL } from '$lib/utils/constants';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ fetch, params, request }) => {
	const backendUrl = `${BASE_API_URL}/compliance-assessments/${params.id}/generate-pdf-report/`;
	try {
		const body = await request.text();
		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'application/pdf, application/json'
		};

		const cookie = request.headers.get('cookie') || '';
		if (cookie) headers['cookie'] = cookie;

		let auth = request.headers.get('authorization');
		if (!auth && cookie) {
			const match = cookie.match(/(?:^|;\s*)token=([^;]+)/);
			if (match) auth = `Token ${decodeURIComponent(match[1])}`;
		}
		if (auth) headers['authorization'] = auth;

		const csrfToken = request.headers.get('x-csrftoken');
		if (csrfToken) headers['x-csrftoken'] = csrfToken;

		const res = await fetch(backendUrl, {
			method: 'POST',
			headers,
			body
		});

		const contentType = res.headers.get('content-type') || 'application/pdf';
		const disposition = res.headers.get('content-disposition');
		const responseHeaders: Record<string, string> = {
			'Content-Type': contentType
		};
		if (disposition) {
			responseHeaders['Content-Disposition'] = disposition;
		}

		const data = await res.arrayBuffer();
		return new Response(data, {
			status: res.status,
			headers: responseHeaders
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}
};

export const GET: RequestHandler = async ({ fetch, params, request }) => {
	const backendUrl = `${BASE_API_URL}/compliance-assessments/${params.id}/generate-pdf-report/`;
	try {
		const headers: Record<string, string> = {
			'Accept': 'application/pdf, application/json'
		};

		const cookie = request.headers.get('cookie') || '';
		if (cookie) headers['cookie'] = cookie;

		let auth = request.headers.get('authorization');
		if (!auth && cookie) {
			const match = cookie.match(/(?:^|;\s*)token=([^;]+)/);
			if (match) auth = `Token ${decodeURIComponent(match[1])}`;
		}
		if (auth) headers['authorization'] = auth;

		const res = await fetch(backendUrl, {
			method: 'GET',
			headers
		});

		const contentType = res.headers.get('content-type') || 'application/pdf';
		const disposition = res.headers.get('content-disposition');
		const responseHeaders: Record<string, string> = {
			'Content-Type': contentType
		};
		if (disposition) {
			responseHeaders['Content-Disposition'] = disposition;
		}

		const data = await res.arrayBuffer();
		return new Response(data, {
			status: res.status,
			headers: responseHeaders
		});
	} catch (err: any) {
		return new Response(JSON.stringify({ error: err.message }), {
			status: 500,
			headers: { 'Content-Type': 'application/json' }
		});
	}
};
