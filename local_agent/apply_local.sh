#!/bin/bash
set -e

JOI_AGENT_DIR=/home/tester/joi-agent
JOI_NEW_DIR=/home/ikess/joi-llm/joi_new/local_agent

cd "$JOI_AGENT_DIR"

sed -i 's/from agent\.joi_agent import JOIAgentManager/from agent.local_agent import LocalAgentManager/' backend/main.py
sed -i 's/manager = JOIAgentManager()/manager = LocalAgentManager()/' backend/main.py
sed -i 's/from agent\.joi_agent import set_mcp_server_url/from agent.local_agent import set_mcp_server_url/' backend/main.py

cp "$JOI_NEW_DIR/local_agent.py" agent/local_agent.py
cp "$JOI_NEW_DIR/../tools.py" agent/tools.py
cp "$JOI_NEW_DIR/../config.py" agent/config.py
cp "$JOI_NEW_DIR/.env" .env

echo "done"
