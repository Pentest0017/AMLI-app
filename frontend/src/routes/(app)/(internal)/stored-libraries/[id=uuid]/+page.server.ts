import { BASE_API_URL } from '$lib/utils/constants';
import { safeTranslate } from '$lib/utils/i18n';
import { m } from '$paraglide/messages';
import { fail, type Actions } from '@sveltejs/kit';
import { setFlash } from 'sveltekit-flash-message/server';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, params }) => {
	const endpoint = `${BASE_API_URL}/stored-libraries/${params.id}/`;
	const treeEndpoint = `${BASE_API_URL}/stored-libraries/${params.id}/tree/`;

	let library: any = {};
	try {
		const res = await fetch(endpoint);
		if (res.ok) {
			library = await res.json();
		} else {
			console.error(`Failed to fetch stored-library ${params.id}:`, res.status);
		}
	} catch (e) {
		console.error(`Error fetching stored-library ${params.id}:`, e);
	}

	const treePromise = fetch(treeEndpoint)
		.then((res) => {
			if (!res.ok) return {};
			return res.json();
		})
		.catch((err) => {
			console.error('Error fetching tree:', err);
			return {};
		});

	return {
		library,
		tree: treePromise,
		title: library?.name || 'Library Detail'
	};
};

export const actions: Actions = {
	load: async (event) => {
		const endpoint = `${BASE_API_URL}/stored-libraries/${event.params.id}/import/`;
		const res = await event.fetch(endpoint, { method: 'POST' });
		if (!res.ok) {
			const response = await res.json();
			console.error('server response:', response);
			setFlash({ type: 'error', message: safeTranslate(response.error) }, event);
			return fail(400, { error: m.errorLoadingLibrary() });
		}
		setFlash(
			{
				type: 'success',
				message: m.librarySuccessfullyLoaded()
			},
			event
		);
	},

	unload: async (event) => {
		const endpoint = `${BASE_API_URL}/stored-libraries/${event.params.id}/unload/`;
		const res = await event.fetch(endpoint, { method: 'POST' });
		if (!res.ok) {
			const response = await res.json();
			console.error('server response:', response);
			setFlash({ type: 'error', message: safeTranslate(response.error) }, event);
			return fail(400, { error: m.errorUnloadingLibrary() });
		}
		setFlash(
			{
				type: 'success',
				message: m.librarySuccessfullyUnloaded()
			},
			event
		);
	}
};
