import { BASE_API_URL } from '$lib/utils/constants';
import type { PageServerLoad, Actions } from './$types';

import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch, locals }) => {
	const user = locals.user;
	const isAuthorizedReviewer = Boolean(
		user?.is_superuser ||
		user?.platform_role === 'superadmin' ||
		user?.platform_role === 'webadmin' ||
		user?.platform_role === 'admin'
	);
	if (!isAuthorizedReviewer) {
		throw redirect(303, '/control-assignments/submit');
	}

	try {
		const ctrlRes = await fetch(`${BASE_API_URL}/control-assignments/controls/`);
		const repoRes = await fetch(`${BASE_API_URL}/evidence-repository/?review_status=PENDING_REVIEW`);

		let frameworks: any[] = [];
		if (ctrlRes.ok) {
			const cData = await ctrlRes.json();
			frameworks = (cData.frameworks || []).map((fw: any) => ({ id: fw.id, name: fw.name }));
		}

		let pendingReviews: any[] = [];
		if (repoRes.ok) {
			const repoData = await repoRes.json();
			const allLinks = repoData.results || repoData || [];
			const user = locals.user;
			const isSuperOrWebAdmin = Boolean(
				user?.is_superuser ||
				user?.platform_role === 'superadmin' ||
				user?.platform_role === 'webadmin'
			);

			// ONLY show controls where evidence HAS BEEN SUBMITTED (PENDING_REVIEW)
			// AND user is Webadmin/Superadmin OR assigned as Reviewer
			pendingReviews = allLinks.filter((link: any) => {
				if (link.review_status !== 'PENDING_REVIEW') return false;
				if (isSuperOrWebAdmin) return true;
				const reviewerEmail = link.control?.reviewer;
				return !reviewerEmail || reviewerEmail.toLowerCase() === user?.email?.toLowerCase();
			});
		}

		return { reviewControls: pendingReviews, frameworks, currentUser: locals.user || null };
	} catch (err) {
		console.error('Error loading reviewer controls:', err);
		return { reviewControls: [], frameworks: [], currentUser: locals.user || null };
	}
};

export const actions: Actions = {
	reviewAction: async ({ fetch, request }) => {
		try {
			const formData = await request.formData();
			const link_id = formData.get('link_id')?.toString();
			const status = formData.get('status')?.toString();
			const feedback = formData.get('feedback')?.toString() || '';
			const expiry_date = formData.get('expiry_date')?.toString() || null;
			const version = formData.get('version')?.toString() || null;

			if (!link_id || !status) {
				return { success: false, error: 'Link ID and status are required.' };
			}

			const res = await fetch(`${BASE_API_URL}/evidence-management/review/${link_id}/`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					status,
					feedback,
					expiry_date,
					version
				})
			});

			if (res.ok) {
				const data = await res.json();
				return { success: true, data };
			} else if (res.status === 409) {
				const conflictData = await res.json();
				return { success: false, conflict: true, error: conflictData.message || 'Conflict: Modified by another reviewer.' };
			} else {
				let errText = 'Failed to submit review.';
				try {
					const err = await res.json();
					errText = err.error || errText;
				} catch (e) {}
				return { success: false, error: errText };
			}
		} catch (err: any) {
			return { success: false, error: err.message || 'Server error submitting review.' };
		}
	}
};
