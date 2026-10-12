import { m } from '$paraglide/messages';
import { toCamelCase } from '$lib/utils/locales';

function formatTitleCase(str: string): string {
	if (!str) return '';
	if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(str)) {
		return str;
	}
	const result = str.replace(/([a-z])([A-Z])/g, '$1 $2').trim();
	return result.charAt(0).toUpperCase() + result.slice(1);
}

/**
 * Unsafe translate function that doesn't return anything if the translation is not found.
 */
export function unsafeTranslate(
	key: string | { day?: number; hour?: number; minute?: number },
	params = {},
	options = {}
): string | undefined {
	try {
		if (
			typeof key === 'object' &&
			key !== null &&
			'day' in key &&
			'hour' in key &&
			'minute' in key
		) {
			const { day, hour, minute } = key;
			const parts = [];
			if (day !== undefined && day !== 0) parts.push(`${m['dayCount']({ count: day }, options)}`);
			if (hour !== undefined && hour !== 0)
				parts.push(`${m['hourCount']({ count: hour }, options)}`);
			if (minute !== undefined && minute !== 0)
				parts.push(`${m['minuteCount']({ count: minute }, options)}`);
			return parts.join(', ');
		}

		if (Object.hasOwn(m, key) && typeof m[key] === 'function') {
			return m[key](params, options);
		}

		if (typeof key === 'string' && key.includes(':')) {
			const sanitizedKey = toCamelCase(
				key
					.replace(/[^\w\s]/g, ' ')
					.replace(/\s+/g, ' ')
					.trim()
			);
			if (sanitizedKey && Object.hasOwn(m, sanitizedKey) && typeof m[sanitizedKey] === 'function') {
				return m[sanitizedKey](params, options);
			}
		}

		if (typeof key === 'string' && key) {
			let res = key.match('^([^:]+):([^:]+)$');
			if (res) {
				return (
					(Object.hasOwn(m, res[1]) && typeof m[res[1]] === 'function'
						? m[res[1]](params, options)
						: res[1]) +
					':' +
					res[2]
				);
			}
		}

		if (Object.hasOwn(m, toCamelCase(key)) && typeof m[toCamelCase(key)] === 'function') {
			return m[toCamelCase(key)](params, options);
		}

		if (typeof key === 'boolean') {
			return key ? '✅' : '❌';
		}
		if (key === 'YES') {
			return '✅';
		}
		if (key === 'NO') {
			return '❌';
		}

		if (typeof key === 'string' && key.includes('->')) {
			const parts = key.split('->');
			if (parts.length === 2) {
				const [from, to] = parts;
				const translatedFrom = m[toCamelCase(from)] ? m[toCamelCase(from)](params, options) : formatTitleCase(from);
				const translatedTo = m[toCamelCase(to)] ? m[toCamelCase(to)](params, options) : formatTitleCase(to);
				return translatedFrom + '->' + translatedTo;
			}
		}

		if (typeof key === 'string' && key.includes('/')) {
			const parts = key.split('/');
			const translatedParts = parts.map((part) => {
				const camelCasePart = toCamelCase(part);
				return m[camelCasePart] ? m[camelCasePart](params, options) : formatTitleCase(part);
			});
			return translatedParts.join('/');
		}
	} catch (e) {
		console.error(`Error translating key "${key}"`, e);
	}
}

/**
 * Safe translate function that returns key formatted as Title Case if translation is not found.
 */
export function safeTranslate(key: string, params = {}, options = {}): string {
	const val = unsafeTranslate(key, params, options);
	if (val) return val;
	return formatTitleCase(key);
}
