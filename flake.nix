{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, utils, ... }:
    {
      nixosModules.default = import ./nixos.nix self;
    } //
    (utils.lib.eachSystem ["x86_64-linux"] (system:
      with nixpkgs.legacyPackages.${system}.python3Packages;
      let
        pkgs = nixpkgs.legacyPackages.${system};

        ngt = buildPythonPackage rec {
          pname = "ngt";
          version = "v2.5.0";

          src = pkgs.fetchFromGitHub {
            owner = "yahoojapan";
            repo = "NGT";
            rev = version;
            hash = "sha256-2cCuVeg7y3butTIAQaYIgx+DPqIFEA2qqVe3exAoAY8=";
          };

          postPatch = ''
            substituteInPlace python/src/ngtpy.cpp \
              --replace-fail "NGT_VERSION" '"${version}"'
          '';

          preConfigure = ''
            export HOME=$PWD
            cd python
          '';

          format = "pyproject";
          build-system = [ setuptools ];
          buildInputs = [ pkgs.ngt ] ++ pkgs.ngt.buildInputs;
          propagatedBuildInputs = [ numpy pybind11 ];
        };

        # In a uniquely named variable for Python Semantic Release
        axynVersion = "8.17.2";

        axyn = buildPythonApplication rec {
          pname = "axyn";
          version = axynVersion;
          src = ./.;

          format = "pyproject";
          build-system = [ setuptools ];

          propagatedBuildInputs = [
            alembic
            discordpy
            fastembed
            ngt
            opentelemetry-api
            opentelemetry-exporter-otlp-proto-http
            opentelemetry-instrumentation-sqlalchemy
            opentelemetry-sdk
            sqlalchemy
          ] ++ sqlalchemy.optional-dependencies.aiosqlite;

          nativeCheckInputs = [
            pkgs.pyright
            pytest
            pytest-asyncio
          ];

          checkPhase = ''
            pyright "$out"
            pytest
          '';
        };

      in rec {
        checks = packages;

        packages.default = axyn;

        devShells.default = pkgs.mkShell {
          inputsFrom = [ axyn ];
          packages = [ coverage ];
        };
      }));
}
