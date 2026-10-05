package config

#Repository: {
	name: string & =~"^[^/]+/[^/]+$"
	ecosystem: string
	cost: number & >0
	enabled: bool | *true
}

#SkopraedV1: {
	surprise_weight: number & >=0 & <=1
	structural_novelty_weight: number & >=0 & <=1
	museum_weight: number & >=0 & <=1
	museum_disagreement_penalty: number & >=0 & <=1
	tail_risk_penalty: number & >=0 & <=1
	cvar_quantile: number & >=0.5 & <1
	pagerank_damping: number & >0 & <1
	beam_width: int & >=8 & <=4096
	empirical_bayes_strength: number & >0
	empirical_bayes_shrinkage: number & >=0 & <=1
}

#RadarConfig: {
	budget: number & >0
	repositories: [...#Repository]
	poll_interval_seconds: int & >=60
	max_catch_up_multiplier: number & >=1 & <=5
	skopraed_v1: #SkopraedV1
}

config: #RadarConfig & {
	budget: 100
	poll_interval_seconds: 900
	max_catch_up_multiplier: 2.5
	repositories: []
	skopraed_v1: {
		surprise_weight: 0.08
		structural_novelty_weight: 0.06
		museum_weight: 0.12
		museum_disagreement_penalty: 0.08
		tail_risk_penalty: 0.11
		cvar_quantile: 0.75
		pagerank_damping: 0.84
		beam_width: 128
		empirical_bayes_strength: 4.0
		empirical_bayes_shrinkage: 0.35
	}
}
