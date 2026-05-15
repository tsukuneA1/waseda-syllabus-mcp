rootのpyproject.tomlにはtool.uv.workspaceでworkspaceに含めたいディレクトリをglobで指定。menberに含まれる各ディレクトリにはpyproject.tomlが必要。

workspace内のパッケージへの依存はdependenciesに書く。
uv syncでvenv(依存)を作る。dockerの場合必要なものはvenvだけなのでuv syncでbuilder stageで.venvを作ってからruntime stageではbuilderから.venvだけコピーしてソースやビルド用キャッシュやdev dependenciesを入れず軽量なイメージを作る。

venvはproject専用のPython実行環境。.venv/lib以下にはdependenciesで指定したライブラリ本体が入っている。PyPIなどから取ってきた依存ライブラリのPythonコード一式。メタデータ、CLIコマンド、ネイティブ拡張なども含まれる。
bin/にはコマンドが入り、実行コマンドが出来る。
dockerfileなどで
```Dockerfile
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:$PATH"
```
して
```bash
uvicorn app.main:app
```
を実行したときにapp/.venv/bin/uvicornが使われる。
uv sync --no-editableなら自分のアプリやworkspace内のpackageも全て.venv/site-packages/にコピー・インストールされる。
