
ifneq ($(shell which docker-compose 2>/dev/null),)
    DOCKER_COMPOSE := docker-compose
else
    DOCKER_COMPOSE := docker compose
endif

dev:
	@lsof -ti :8081 | xargs kill 2>/dev/null || true
	@lsof -ti :5173 | xargs kill 2>/dev/null || true
	@sleep 1
	@echo "Starting backend and frontend..."
	cd backend && ./dev.sh &
	@echo "Waiting for backend to be ready..."
	@for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do \
		curl -sf http://localhost:8081/api/config > /dev/null 2>&1 && break; \
		sleep 1; \
	done
	@curl -sf http://localhost:8081/api/config > /dev/null 2>&1 \
		&& echo "Backend ready on :8081" \
		|| echo "WARNING: Backend may not be ready yet"
	npm run dev

install:
	$(DOCKER_COMPOSE) up -d

remove:
	@chmod +x confirm_remove.sh
	@./confirm_remove.sh

start:
	$(DOCKER_COMPOSE) start
startAndBuild: 
	$(DOCKER_COMPOSE) up -d --build

stop:
	$(DOCKER_COMPOSE) stop

update:
	# Calls the LLM update script
	chmod +x update_ollama_models.sh
	@./update_ollama_models.sh
	@git pull
	$(DOCKER_COMPOSE) down
	# Make sure the ollama-webui container is stopped before rebuilding
	@docker stop open-webui || true
	$(DOCKER_COMPOSE) up --build -d
	$(DOCKER_COMPOSE) start

pull-models:
	@echo "Pulling Ollama models into Docker volume..."
	docker exec ollama ollama pull llama3.2
	@echo "Models pulled. Add more with: docker exec ollama ollama pull <model>"

export-images:
	@echo "Exporting Docker images for airgap transfer..."
	docker save -o myofflineai-images.tar ollama/ollama ghcr.io/open-webui/open-webui
	@echo "Saved to myofflineai-images.tar"

load-images:
	@echo "Loading Docker images from archive..."
	docker load -i myofflineai-images.tar
	@echo "Images loaded. Run 'make install' to start."

