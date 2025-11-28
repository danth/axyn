self:
{ pkgs, config, lib, ... }:

with lib;

let
  axyn = self.packages.${pkgs.system}.default;

  cfg = config.services.axyn;

in {
  options.services.axyn = {
    enable = mkEnableOption "Axyn";

    tokenPath = mkOption {
      description = "Path to a file containing the Discord token.";
      type = types.path;
    };
  };

  config.systemd.services.axyn = mkIf cfg.enable {
    description = "Axyn";

    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    wantedBy = [ "default.target" ];

    script = ''
      export DISCORD_TOKEN="$(cat "$CREDENTIALS_DIRECTORY/token")"
      export HOME="$STATE_DIRECTORY"
      exec ${axyn}/bin/axyn
    '';

    serviceConfig = {
      DynamicUser = true;
      StateDirectory = "axyn";
      LoadCredential = "token:${cfg.tokenPath}";
      Restart = "on-failure";

      # Security hardening
      CapabilityBoundingSet = "";
      LockPersonality = true;
      ProtectClock = true;
      ProtectControlGroups = true;
      PrivateDevices = true;
      ProtectHome = true;
      ProtectHostname = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      ProtectProc = "invisible";
      PrivateUsers = true;
      RestrictAddressFamilies = [ "AF_INET" "AF_INET6" ];
      RestrictNamespaces = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;
      SystemCallArchitectures = "native";
      SystemCallFilter = "@system-service";
    };
  };
}

