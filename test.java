public class test {
    public static void main(String[] args) {
        String osName = System.getProperty("os.name");
        String osVersion = System.getProperty("os.version");
        String osArch = System.getProperty("os.arch");
        String javaVendor = System.getProperty("java.vendor");
        String javaVersion = System.getProperty("java.version");
        String javaVendorVersion = System.getProperty("java.vm.version");
        System.out.println(String.format("Gradle/%s (%s;%s;%s) (%s;%s;%s)",
                "8.1.1", // GradleVersion.current().getVersion(),
                osName,
                osVersion,
                osArch,
                javaVendor,
                javaVersion,
                javaVendorVersion));
    }
}
