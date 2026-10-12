.PHONY: install install-ml test demo sim experiment stream-eval

install:
	pip install -e ".[dev]"

install-ml:
	pip install -e ".[dev,ml]"

test:
	pytest -q

demo:
	wfg demo

sim:
	wfg simulate --rooms sim_a sim_b sim_c sim_d --clips 30 --out data/sim

experiment: sim
	wfg experiment --data data/sim --methods classic classic+restd cnn1d cnn1d+mmd cnn1d+dann cnn1d+ft cnn1d+knnmmd \
		--shots 0 1 5 --seeds 0 1 2 --out results/sim

stream-eval:
	wfg stream-eval --model models/classic_sim.npz --rooms demo unseen_1 unseen_2
