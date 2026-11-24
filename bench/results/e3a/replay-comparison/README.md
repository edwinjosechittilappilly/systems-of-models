# Replay comparison evidence

These ordered shards contain one gzip stream of the comparator's JSON output, including the raw diffs. They preserve every byte of the original output except that two occurrences of the original absolute repository-root prefix were replaced with `<REPO_ROOT>` for privacy. The redaction does not change the comparison results. The original unredacted JSON was 319,972,913 bytes with SHA-256 `9384d41bd8db531b81483ed3b24c720b1abec129502b57f6c5f90383fff72af6`.

From the repository root, reconstruct the redacted JSON (approximately 320 MB):

```sh
cat bench/results/e3a/replay-comparison/comparison.json.gz.part-* | gzip -dc > /tmp/e3a-replay-comparison.redacted.json
```

To reconstruct the original bytes, provide the **original** repository-root prefix privately in `ORIGINAL_REPO_ROOT`; a different checkout path will not reproduce the original hash. This writes private path information to the output file; do not commit or publish it.

```sh
export ORIGINAL_REPO_ROOT='the original absolute repository root'
python3 -c 'import os, pathlib; p = pathlib.Path("/tmp/e3a-replay-comparison.redacted.json"); b = p.read_bytes(); assert b.count(b"<REPO_ROOT>") == 2; pathlib.Path("/tmp/e3a-replay-comparison.original.json").write_bytes(b.replace(b"<REPO_ROOT>", os.fsencode(os.environ["ORIGINAL_REPO_ROOT"])))'
shasum -a 256 /tmp/e3a-replay-comparison.original.json
```

The comparison records the replay results. Input traces are in the separately transferred local archive described in `../ARTIFACTS.md`; model caches needed to rerun the replay are local and are not included in that archive or these shards.

## Shard SHA-256 checksums

Each shard is at most 900,000 bytes. Run `shasum -a 256 -c` on the following lines from this directory to verify them.

```text
12eb66a0554205fb1a9252d0933c1b26d9a8e0fcadf24210820231c833bd6ed4  comparison.json.gz.part-0000
049be4018931b6ac2705f789aae7c49cd12ad5db183e1d0eedc762ca69303f8e  comparison.json.gz.part-0001
c25b3c305821e876a23570447ef6f6ec21f458e9a0289a8314ed907ce2ae7c21  comparison.json.gz.part-0002
25052abde7b88c913732721ef1acbb0bfa5c68de6b2365896ed45b9a69fd5545  comparison.json.gz.part-0003
8f92f5013a7bccea2daee7adf1eef0e25e1ef2fa2173fd1247418fa0e765a048  comparison.json.gz.part-0004
615a26ccbc9121da812f651d1bed7b8cc83cad6982d3f92a10d9f15ae61b4c1f  comparison.json.gz.part-0005
5dbbb8682b19aeabc8097f66bb3219c89c931e32950e2ffb8a6c3ec027798227  comparison.json.gz.part-0006
44f45d94f0e8abe2744e40b51222fe5e37a34883f5aece7a9a26fb548bdf8de6  comparison.json.gz.part-0007
c07d922f948e49489530399d2fd8846276afd20b1efdf9b7727942649cd9ef8b  comparison.json.gz.part-0008
fc4fe40cf563ed81f3e2ad4bc1bb9c1691f777e4a9d6a0c295bf7023e46b7fc0  comparison.json.gz.part-0009
0fdd5c0284dba0f0392a93b836f698e6e5834629c123305239f596b0ca6fad25  comparison.json.gz.part-0010
a704ddf747c7b2620ed6330d449a70784bec7a07404352937126e61a1e4a3769  comparison.json.gz.part-0011
271f1bb4518c598797dce2a5c591cb4f3f80de5d0c25be850b8e6bf5538312f9  comparison.json.gz.part-0012
7f99d0ea2d4e0b5dc3dbb782c4c9a94966bce895d5862d4a7344dffa14265144  comparison.json.gz.part-0013
8e05fc526a32b7d172a942246f9db5d7692032ea37a48c3a1c274b182deb757c  comparison.json.gz.part-0014
2d82a454fba63b34d27177b2f0b7d7c81ba0db8787a6a4d620a64b14629654c0  comparison.json.gz.part-0015
3a733c67b9c98419c332598b52cd0a6e8427fa2e450c2287d920cd948db07a40  comparison.json.gz.part-0016
cfbeb79c88af1c1e18e0da7b22d0242c6b3ba3093203a5dfc74f28370e618623  comparison.json.gz.part-0017
9059ccc8170d1af9e8c9b9fe1df3ba2c55108028c61a27233074ca1302b72acb  comparison.json.gz.part-0018
e0e5c211a059a2efe6c90b1467cc6c42718d287c667faa9805ee93f672129797  comparison.json.gz.part-0019
474d2416eae02e4ef23f3c7848ba78151636787fb9765f99b10df14435cdfa1d  comparison.json.gz.part-0020
2dad5a3fdfcd014623a4fe69a6a3c9da41c2957c27e0d788e59825c3f0c9a179  comparison.json.gz.part-0021
f1885fa1f52677f67e6bfd87d377d5a70a57a00da0f712434c1997de9b1e040a  comparison.json.gz.part-0022
584bc97dcaf1c8cb141d3604863c7e4b04c9b1e51d1f03c48a313859878f1f6b  comparison.json.gz.part-0023
2c28efb9d20612a248bb966a6024e0c7691cd456cb585c0184cb5573d571fce3  comparison.json.gz.part-0024
88423eed860eb34938111fe2ca9331753c06da956d25bdff9256cd8f89c0836c  comparison.json.gz.part-0025
fab6865b50e705740ca00d455b37a751a41405e64e5d37dd5b576d1c7d087df8  comparison.json.gz.part-0026
49fe83d19bd9ea4d5b2da547669f78811156a0727eb34d92a6b43415001fe838  comparison.json.gz.part-0027
edf6fef8be2c261fe17f01602b29ea4b1d59cbeae23cf8553ce9ed8c99e30fba  comparison.json.gz.part-0028
9c2ab8eab8c3a3283c9a911301e6519c9e9c5eeabda17324a76b16667e8876de  comparison.json.gz.part-0029
```
