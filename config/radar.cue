package config

#Repository: {
	name: string & =~"^[^/]+/[^/]+$"
	ecosystem: string
	cost: number & >0
	enabled: bool | *true
}

#RadarConfig: {
	budget: number & >0
	repositories: [...#Repository]
	poll_interval_seconds: int & >=60
	max_catch_up_multiplier: number & >=1 & <=5
}

config: #RadarConfig & {
	budget: 100
	poll_interval_seconds: 900
	max_catch_up_multiplier: 2.5
	repositories: []
}
