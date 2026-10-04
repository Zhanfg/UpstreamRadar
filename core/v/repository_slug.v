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


pub fn structural_entropy(parts []string) f64 {
	if parts.len == 0 {
		return 0.0
	}
	mut freq := map[string]int{}
	for part in parts {
		freq[part]++
	}
	mut entropy := 0.0
	total := f64(parts.len)
	for _, count in freq {
		p := f64(count) / total
		entropy -= p * log2(p)
	}
	max_entropy := log2(total)
	if max_entropy <= 0.0 {
		return 0.0
	}
	return (entropy / max_entropy).clamp(0.0, 1.0)
}

pub fn slug_novelty(raw string) !f64 {
	slug := normalize(raw)!
	parts := slug.replace('-', '.').replace('_', '.').split('.')
	return structural_entropy(parts.filter(it.len > 0))
}
