package org.robotframework.formslibrary.operator;

import java.awt.Component;
import java.awt.TextField;
import java.awt.event.FocusEvent;
import org.netbeans.jemmy.ComponentChooser;
import org.robotframework.formslibrary.FormsLibraryException;
import org.robotframework.formslibrary.util.ComponentUtil;
import org.robotframework.formslibrary.util.Logger;
import org.robotframework.formslibrary.util.ObjectUtil;
import org.robotframework.formslibrary.util.TextUtil;

import java.awt.event.FocusEvent;

import org.robotframework.formslibrary.FormsLibraryException;
import org.robotframework.formslibrary.chooser.ByNameChooser;
import org.robotframework.formslibrary.util.ComponentType;
import org.robotframework.formslibrary.util.ObjectUtil;

/**
 * Operator for working with standard text and text area fields.
 */
public class TextFieldOperator extends AbstractComponentOperator {

	/**
	 * Initialize a TextFieldOperator for the given field.
	 */
	public TextFieldOperator(Component component) {
		super(component);
	}

	/**
	 * Initialize a TextFieldOperator using the provided chooser.
	 */
	public TextFieldOperator(ComponentChooser chooser) {
		super(chooser);
	}

	public TextFieldOperator(String identifier) {
		super(new ByNameChooser(identifier, ComponentType.ALL_TEXTFIELD_TYPES));
	}

	/**
	 * Focus on the field and set the field value.
	 */
	public void setValue(String value) {
		// apply focus to the field, otherwise values are ignored in the
		// searches.
		getSource().dispatchEvent(new FocusEvent(getSource(), FocusEvent.FOCUS_GAINED));
		ObjectUtil.invokeMethodWithStringArg(getSource(), "setText()", value);
		getSource().dispatchEvent(new FocusEvent(getSource(), FocusEvent.FOCUS_LOST));
		Logger.info("Set field value to '" + value + "'.");
	}

	public void push() {
		ComponentUtil.simulateMouseClick(getSource());
		Logger.debug("Button was pushed.");
	}

	/**
	 * @return field content.
	 */
	public String getValue() {
		return ObjectUtil.getString(getSource(), "getText()");
	}

	/**
	 * Verify that the field contains the given value.
	 */
	public void verifyValue(String value) {
		if (!TextUtil.matches(getValue(), value)) {
			throw new FormsLibraryException("Field value '" + getValue() + "' does not match " + value);
		}
		Logger.info("Value '" + getValue() + "' matches '" + value + "'.");
	}

}
