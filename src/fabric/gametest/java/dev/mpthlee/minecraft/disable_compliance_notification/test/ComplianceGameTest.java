package dev.mpthlee.minecraft.disable_compliance_notification.test;

import java.lang.reflect.Method;

import net.fabricmc.fabric.api.gametest.v1.CustomTestMethodInvoker;
import net.fabricmc.fabric.api.gametest.v1.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;

public class ComplianceGameTest implements CustomTestMethodInvoker {

    @GameTest(maxTicks = 50)
    public void basicLoadTest(GameTestHelper helper) {
        helper.succeed();
    }

    @Override
    public void invokeTestMethod(GameTestHelper context, Method method) throws ReflectiveOperationException {
        method.invoke(this, context);
    }
}
