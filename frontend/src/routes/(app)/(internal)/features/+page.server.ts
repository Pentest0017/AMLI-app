import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';
import { fail } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch }) => {
	try {
		const res = await fetch(`${BASE_API_URL}/feature-toggles/?page_size=1000`);
		if (!res.ok) {
			return { toggles: [], error: `Failed to fetch toggles: ${res.statusText}` };
		}
		const data = await res.json();
		return { toggles: data.results || data, error: null };
	} catch (e: any) {
		return { toggles: [], error: e.message || 'Error fetching feature toggles' };
	}
};

export const actions: Actions = {
	save: async ({ request, fetch }) => {
		const formData = await request.formData();
		const togglesRaw = formData.get('toggles');
		if (!togglesRaw || typeof togglesRaw !== 'string') {
			return fail(400, { error: 'Invalid payload' });
		}

		try {
			const togglesList = JSON.parse(togglesRaw);

			// Fetch existing toggles from the backend to match by key/id
			const existingRes = await fetch(`${BASE_API_URL}/feature-toggles/?page_size=1000`);
			const existingMap: Record<string, any> = {};
			if (existingRes.ok) {
				const existingData = await existingRes.json();
				const items = Array.isArray(existingData) ? existingData : existingData.results || [];
				items.forEach((item: any) => {
					if (item.key) existingMap[item.key] = item;
				});
			}

			let hasError = false;
			let errorMessage = '';

			for (const t of togglesList) {
				const existing = t.id ? t : existingMap[t.key];
				const targetId = existing?.id;

				if (targetId) {
					const patchRes = await fetch(`${BASE_API_URL}/feature-toggles/${targetId}/`, {
						method: 'PATCH',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							enabled_for_web_admin: t.enabled_for_web_admin,
							enabled_for_admin: t.enabled_for_admin,
							enabled_for_user: t.enabled_for_user
						})
					});
					if (!patchRes.ok) {
						hasError = true;
						errorMessage = `Failed to update toggle '${t.key}': ${patchRes.statusText}`;
					}
				} else {
					const postRes = await fetch(`${BASE_API_URL}/feature-toggles/`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({
							key: t.key,
							name: t.name || t.key,
							parent_key: t.parent_key || null,
							enabled_for_web_admin: t.enabled_for_web_admin,
							enabled_for_admin: t.enabled_for_admin,
							enabled_for_user: t.enabled_for_user
						})
					});
					if (!postRes.ok) {
						hasError = true;
						errorMessage = `Failed to create toggle '${t.key}': ${postRes.statusText}`;
					}
				}
			}

			if (hasError) {
				return fail(400, { error: errorMessage });
			}

			return { success: true };
		} catch (e: any) {
			return fail(500, { error: e.message || 'Failed to save feature toggles' });
		}
	}
};
