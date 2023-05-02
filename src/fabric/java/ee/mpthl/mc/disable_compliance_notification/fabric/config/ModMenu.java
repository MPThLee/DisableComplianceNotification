package ee.mpthl.mc.disable_compliance_notification.fabric.config;

import com.terraformersmc.modmenu.api.ConfigScreenFactory;
import com.terraformersmc.modmenu.api.ModMenuApi;
import me.shedaniel.autoconfig.AutoConfig;
import ee.mpthl.mc.disable_compliance_notification.config.ConfigHelper;
import me.shedaniel.clothconfig2.api.ConfigScreen;
import net.fabricmc.api.EnvType;
import net.fabricmc.api.Environment;

@Environment(EnvType.CLIENT)
public class ModMenu implements ModMenuApi {
    @Override
    public ConfigScreen<?> getModConfigScreen() {
        return AutoConfig.getConfigScreen(ConfigHelper.class, ConfigScreenFactory.class).get();
    }
}
