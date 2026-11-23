# Run makeglossaries so the glossary shows up (latexmk doesn't do it by default)
add_cus_dep('glo', 'gls', 0, 'run_makeglossaries');
add_cus_dep('acn', 'acr', 0, 'run_makeglossaries');
sub run_makeglossaries {
  my ($base_name, $path) = fileparse($_[0]);
  pushd $path;
  my $return = system "makeglossaries", $base_name;
  popd;
  return $return;
}
push @generated_exts, 'glo', 'gls', 'glg', 'acn', 'acr', 'alg', 'ist';
