package dev.mpthlee.minecraft.disable_compliance_notification.test;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.TitleScreen;

import java.lang.reflect.Field;

/** Exercises optional integrations through their public APIs in the test runtime. */
public final class OptionalConfigCheck {
    private OptionalConfigCheck() {
    }

    public static Screen open(Minecraft client, String loader) {
        String prefix = "dev.mpthlee.minecraft.disable_compliance_notification." + loader + ".config.";
        try {
            Class<?> config;
            try {
                config = Class.forName(prefix + "YACLConfig");
                config.getMethod("createConfigScreen", Screen.class);
                config.getField("HANDLER");
            } catch (ClassNotFoundException | NoSuchMethodException | NoSuchFieldException unsupported) {
                System.out.println("DCN optional config interaction unavailable");
                return null;
            }

            Object handler = config.getField("HANDLER").get(null);
            Class<?> api = Class.forName("dev.isxander.yacl3.config.v2.api.ConfigClassHandler");
            Object instance = api.getMethod("instance").invoke(handler);
            Field setting = config.getField("notificationFilterMode");
            Object original = setting.get(instance);
            Object alternate = java.util.Arrays.stream(setting.getType().getEnumConstants())
                    .filter(value -> value != original).findFirst().orElseThrow();
            try {
                setting.set(instance, alternate);
                api.getMethod("save").invoke(handler);
                setting.set(instance, original);
                api.getMethod("load").invoke(handler);
                if (setting.get(api.getMethod("instance").invoke(handler)) != alternate) {
                    throw new IllegalStateException("YACL setting did not survive save/reload");
                }
            } finally {
                setting.set(api.getMethod("instance").invoke(handler), original);
                api.getMethod("save").invoke(handler);
                Class.forName(prefix + "Config").getMethod("loadConfig").invoke(null);
            }

            Screen parent = new TitleScreen();
            Screen screen;
            if (loader.equals("fabric")) {
                Object bridge = Class.forName(prefix + "ModMenu").getConstructor().newInstance();
                Object factory = Class.forName("com.terraformersmc.modmenu.api.ModMenuApi")
                        .getMethod("getModConfigScreenFactory").invoke(bridge);
                screen = (Screen) Class.forName("com.terraformersmc.modmenu.api.ConfigScreenFactory")
                        .getMethod("create", Screen.class).invoke(factory, parent);
            } else {
                screen = (Screen) config.getMethod("createConfigScreen", Screen.class).invoke(null, parent);
            }
            if (screen == null || screen == parent) {
                throw new IllegalStateException("Optional config integration did not create a screen");
            }
            client.gui.setScreen(screen);
            return screen;
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("Optional config interaction failed", exception);
        }
    }
}
