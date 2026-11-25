import com.sun.source.tree.*;
import com.sun.source.util.*;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.lang.model.element.Modifier;
import javax.tools.*;

/** Run with JDK 17+ from the repository root. Reads the index or commit blobs through Git. */
class CheckJavaParameters {
    private static String git(List<String> arguments) throws Exception {
        List<String> command = new ArrayList<>(List.of("git"));
        command.addAll(arguments);
        Process process = new ProcessBuilder(command).redirectError(ProcessBuilder.Redirect.INHERIT).start();
        String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
        if (process.waitFor() != 0) {
            throw new IOException("Git command failed: " + command);
        }
        return output;
    }

    private static String commit(String ref) throws Exception {
        return git(List.of("rev-parse", "--verify", "--end-of-options", ref + "^{commit}")).strip();
    }

    private static List<String> diffArguments(List<String> args) throws Exception {
        int separator = args.indexOf("--");
        List<String> mode = separator < 0 ? args : args.subList(0, separator);
        List<String> command;
        if (mode.isEmpty()) {
            command = new ArrayList<>(List.of("diff", "--cached"));
        } else if (mode.size() == 2 && mode.get(0).equals("--commit")) {
            command = new ArrayList<>(List.of("diff-tree", "-r", "--root", "--no-commit-id",
                    "--diff-merges=first-parent", commit(mode.get(1))));
        } else if (mode.size() == 3 && mode.get(0).equals("--between")) {
            command = new ArrayList<>(List.of("diff", commit(mode.get(1)), commit(mode.get(2))));
        } else {
            throw new IllegalArgumentException("Usage: java CheckJavaParameters.java [--commit REF | --between BASE TIP] [-- PATH...]");
        }
        command.addAll(List.of("--raw", "-z", "--no-abbrev", "--find-renames", "--diff-filter=AMRT", "--"));
        command.addAll(separator < 0 ? List.of("*.java") : args.subList(separator + 1, args.size()));
        return command;
    }

    private static boolean possibleOverride(ClassTree owner, MethodTree method) {
        if (method.getReturnType() == null || method.getModifiers().getFlags().contains(Modifier.PRIVATE)
                || method.getModifiers().getFlags().contains(Modifier.STATIC)) {
            return false;
        }
        for (AnnotationTree annotation : method.getModifiers().getAnnotations()) {
            if (Set.of("Override", "java.lang.Override").contains(annotation.getAnnotationType().toString())) {
                return true;
            }
        }
        // Parsing alone cannot resolve inherited methods from the project classpath.
        return owner.getExtendsClause() != null || !owner.getImplementsClause().isEmpty()
                || (method.getName().contentEquals("equals") && method.getParameters().size() == 1);
    }

    private static boolean fixedEntryPoint(ClassTree owner, MethodTree method) {
        // Compact record constructors implicitly assign every component after the source body.
        if (owner.getKind() == Tree.Kind.RECORD && method.getReturnType() == null) {
            return true;
        }
        Set<Modifier> flags = method.getModifiers().getFlags();
        return method.getName().contentEquals("main") && flags.contains(Modifier.PUBLIC)
                && flags.contains(Modifier.STATIC) && method.getReturnType().toString().equals("void")
                && method.getParameters().size() == 1
                && Set.of("String[]", "java.lang.String[]").contains(method.getParameters().get(0).getType().toString());
    }

    private static void inspectType(ClassTree type, String parent, CompilationUnitTree unit, SourcePositions positions,
                                    Set<String> previous, Set<String> signatures, List<String> findings) {
        String owner = parent + type.getSimpleName();
        for (Tree member : type.getMembers()) {
            if (member instanceof ClassTree nested) {
                inspectType(nested, owner + ".", unit, positions, previous, signatures, findings);
            }
            if (!(member instanceof MethodTree method)) {
                continue;
            }
            String signature = owner + "." + method.getName() + method.getTypeParameters() + "("
                    + method.getParameters() + "):" + method.getReturnType();
            signatures.add(signature);
            if (previous == null || previous.contains(signature) || method.getBody() == null
                    || method.getParameters().isEmpty() || possibleOverride(type, method) || fixedEntryPoint(type, method)) {
                continue;
            }
            Set<String> referenced = new HashSet<>();
            new TreeScanner<Void, Void>() {
                @Override
                public Void visitIdentifier(IdentifierTree identifier, Void unused) {
                    referenced.add(identifier.getName().toString());
                    return null;
                }
            }.scan(method.getBody(), null);
            for (VariableTree parameter : method.getParameters()) {
                if (!referenced.contains(parameter.getName().toString())) {
                    long offset = positions.getStartPosition(unit, parameter);
                    findings.add(unit.getLineMap().getLineNumber(offset) + ": " + owner + "." + method.getName()
                            + ": remove unused parameter '" + parameter.getName() + "' from the signature and callers, "
                            + "or use it in the operation that needs it.");
                }
            }
        }
    }

    private static Set<String> inspect(String blob, String path, Set<String> previous, List<String> findings) throws Exception {
        String source = git(List.of("cat-file", "blob", blob));
        JavaFileObject file = new SimpleJavaFileObject(URI.create("string:///Source.java"), JavaFileObject.Kind.SOURCE) {
            @Override
            public CharSequence getCharContent(boolean ignoreEncodingErrors) {
                return source;
            }
        };
        DiagnosticCollector<JavaFileObject> diagnostics = new DiagnosticCollector<>();
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        Set<String> signatures = new HashSet<>();
        try (StandardJavaFileManager manager = compiler.getStandardFileManager(diagnostics, null, StandardCharsets.UTF_8)) {
            JavacTask parser = (JavacTask) compiler.getTask(null, manager, diagnostics, List.of("-proc:none"), null, List.of(file));
            for (CompilationUnitTree unit : parser.parse()) {
                SourcePositions positions = Trees.instance(parser).getSourcePositions();
                for (Tree declaration : unit.getTypeDecls()) {
                    if (declaration instanceof ClassTree type) {
                        inspectType(type, "", unit, positions, previous, signatures, findings);
                    }
                }
            }
            for (Diagnostic<?> diagnostic : diagnostics.getDiagnostics()) {
                if (diagnostic.getKind() == Diagnostic.Kind.ERROR) {
                    throw new IOException(path + ":" + diagnostic.getLineNumber() + " (" + blob + "): "
                            + diagnostic.getMessage(Locale.ROOT));
                }
            }
        }
        return signatures;
    }

    private static int check(List<String> args) throws Exception {
        String[] fields = git(diffArguments(args)).split("\0");
        int checked = 0;
        int count = 0;
        for (int i = 0; i < fields.length && !fields[i].isEmpty();) {
            String[] entry = fields[i++].split(" ");
            String oldPath = fields[i++];
            String path = entry[4].startsWith("R") ? fields[i++] : oldPath;
            if (!path.endsWith(".java") || !entry[1].startsWith("100")) {
                continue;
            }
            checked++;
            List<String> findings = new ArrayList<>();
            Set<String> previous = entry[0].startsWith(":100") && oldPath.endsWith(".java")
                    ? inspect(entry[2], oldPath, null, findings) : Set.of();
            inspect(entry[3], path, previous, findings);
            for (String finding : findings) {
                System.out.println(path + ":" + finding);
            }
            count += findings.size();
        }
        System.out.println("Checked " + checked + " changed Java file(s); " + count + " unused parameter(s).");
        return count == 0 ? 0 : 1;
    }

    public static void main(String[] args) {
        try {
            System.exit(check(Arrays.asList(args)));
        } catch (Exception error) {
            System.err.println(error.getMessage());
            System.exit(2);
        }
    }
}
