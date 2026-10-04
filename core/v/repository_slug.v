module repository_slug

pub fn normalize(raw string) !string {
	mut value := raw.trim_space().to_lower()
	if value.starts_with('https://github.com/') {
		value = value.trim_string_left('https://github.com/')
	}
	if value.ends_with('.git') {
		value = value[..value.len - 4]
	}
	value = value.trim('/')
	parts := value.split('/')
	if parts.len != 2 || parts[0].len == 0 || parts[1].len == 0 {
		return error('expected owner/repository')
	}
	for ch in value {
		if !(ch.is_alnum() || ch in [`-`, `_`, `.`, `/`]) {
			return error('invalid repository slug')
		}
	}
	return value
}
