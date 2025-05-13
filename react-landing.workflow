run = "./run_react_landing.sh"
language = "nodejs"
entrypoint = "run_react_landing.sh"
channel = "stable-22_11"
hidden = false
onBoot = false
modules = ["nodejs-20:v1-20240313-46fee33"]
id = "react-landing"

[nix]
channel = "stable-23_11"

[deployment]
deploymentTarget = "cloudrun"
ignorePorts = false
run = ["sh", "./run_react_landing.sh"]