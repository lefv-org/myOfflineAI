import { WEBUI_API_BASE_URL } from '$lib/constants';

export type BrowseResult = {
	path: string;
	dirs: string[];
};

export const browseDirectories = async (
	token: string,
	path?: string
): Promise<BrowseResult> => {
	let error: any = null;
	const params = path ? `?path=${encodeURIComponent(path)}` : '';

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/browse${params}`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export type WatchedDirectory = {
	id: string;
	path: string;
	name: string;
	knowledge_id: string | null;
	extensions: string | null;
	exclude_patterns: string | null;
	enabled: boolean;
	last_scan_at: number | null;
	created_at: number;
	updated_at: number;
};

export type WatchedDirectoryForm = {
	path: string;
	name: string;
	extensions?: string | null;
	exclude_patterns?: string | null;
};

export type DirectoryStats = {
	id: string;
	file_count: number;
	last_scan_age_seconds: number | null;
};

export type FilesystemStats = {
	total_files: number;
	completed_files: number;
	pending_files: number;
	failed_files: number;
	total_chunks: number;
	vector_db_size_bytes: number;
	file_types: Record<string, number>;
	directories: DirectoryStats[];
};

export const getWatchedDirectories = async (token: string): Promise<WatchedDirectory[]> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const createWatchedDirectory = async (
	token: string,
	form: WatchedDirectoryForm
): Promise<WatchedDirectory> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateWatchedDirectory = async (
	token: string,
	id: string,
	form: WatchedDirectoryForm
): Promise<WatchedDirectory> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}`, {
		method: 'PUT',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		body: JSON.stringify(form)
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const deleteWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const resyncWatchedDirectory = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}/resync`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getFilesystemStats = async (token: string): Promise<FilesystemStats> => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/stats`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const clearDirectoryIndex = async (token: string, id: string) => {
	let error: any = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/filesystem/${id}/index`, {
		method: 'DELETE',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
