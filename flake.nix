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

        discordhealthcheck = buildPythonPackage rec {
          pname = "discordhealthcheck";
          version = "0.1.1";

          src = pkgs.fetchFromGitHub {
            owner = "psidex";
            repo = "DiscordHealthCheck";
            rev = "1822ca34190fb34cb51779876ba3aebd760219fb";
            hash = "sha256-icFlbOTJtFfZJC4A4Fz7c6/aXT1vaFgmkBbBmdScBxM=";
          };

          format = "pyproject";
          build-system = [ setuptools ];
          propagatedBuildInputs = [ discordpy ];
        };

        sqlalchemy-boltons = buildPythonPackage rec {
          pname = "sqlalchemy_boltons";
          version = "4.0.1";

          src = pkgs.fetchPypi {
            inherit pname version;
            hash = "sha256-YvmZ5PWwYYL2HXBbIHps8K//qVVj0zLJ38mF5dR0SkU=";
          };

          format = "pyproject";
          build-system = [ setuptools ];
          propagatedBuildInputs = [ immutabledict sqlalchemy ];
          nativeCheckInputs = [ pytest ];
          checkPhase = "pytest";
        };

        # In a uniquely named variable for Python Semantic Release
        axynVersion = "8.10.3";

        axyn = buildPythonApplication rec {
          pname = "axyn";
          version = axynVersion;
          src = ./.;

          format = "pyproject";
          build-system = [ setuptools ];

          propagatedBuildInputs = [
            alembic
            discordhealthcheck
            discordpy
            fastembed
            ngt
            sqlalchemy
            sqlalchemy-boltons
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

      in {
        packages.default = axyn;

        devShells.default = pkgs.mkShell {
          inputsFrom = [ axyn ];
          packages = [ coverage ];
        };
      }));
}
